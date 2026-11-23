# Integração Firebase do passageiro

Atualizado em 10/11/2026. Este documento descreve o código atual; o PDF de 21/10 permanece como referência histórica do backend operacional.

## Arquitetura

`página → hooks/transit → TransitService → mock | REST | Firebase`.

O adaptador Firebase autentica anonimamente quando não existe uma sessão, consulta somente as coleções públicas e observa `/telemetry` no RTDB. O papel operacional continua vindo da claim do token; uma sessão anônima não recebe privilégios de motorista ou dono. A localização do passageiro é usada localmente para ordenar pontos, sem envio ao Firebase.

| Coleção                    | Conteúdo permitido                                                                                         |
| -------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `public_lines/{linhaId}`   | Número, nome, cor, operação, intervalo, IDs ordenados de paradas, traçado, frações e indicador de circular |
| `public_stops/{pontoId}`   | Nome, referência, latitude e longitude                                                                     |
| `public_buses/{busId}`     | Prefixo público, linha e sentido                                                                           |
| `public_notices/{avisoId}` | Tipo, título, descrição, números de linhas e horário textual                                               |

Todas exigem autenticação para leitura e negam escrita ao cliente. `buses` privado é lido somente pelo motorista ativo ou pelo dono da frota com claim adequada. `users`, `drivers` e rotas operacionais conservam suas regras. O RTDB permanece autenticado, sem escrita direta; não contém identidade de motorista.

O catálogo público é deliberadamente separado das rotas privadas: publicar uma linha não torna uma rota operacional legível. `public_buses.linhaId` é o vínculo explícito do veículo à linha de passageiro, mantido pelo administrador. Alterar `drivers.id_route` não muda esse vínculo automaticamente: são contratos distintos.

## Configuração local

1. Copie `.env.example` para `.env.local`.
2. Defina `VITE_DATA_SOURCE=firebase` e mantenha `VITE_USE_EMULATORS=true`.
3. Inicie Auth, Firestore, Database e Functions pelos comandos em `backend/README.md`, usando uma cópia dos exports quando precisar dos dados existentes.
4. Publique um catálogo revisado no emulador com a ferramenta abaixo.
5. Um motorista autenticado faz `checkIn` e envia `sendTelemetry` normalmente. As telas recebem a projeção no próximo heartbeat.

As portas padrão são Auth 9099, Firestore 8080, RTDB 9000 e Functions 5001. Ajuste as variáveis `VITE_*_PORT` se usar outras portas. Sessões existentes são preservadas; consultas paralelas compartilham a autenticação inicial. Falhas têm timeout e retry na interface.

## Publicação do catálogo

O arquivo JSON possui exatamente `lines`, `stops`, `buses`, `notices`, todos arrays. Não inclua senhas, UIDs, tags, placas ou vínculos internos. Exemplo mínimo de formato (coordenadas ilustrativas; não é uma rota homologada):

```json
{
  "lines": [
    {
      "id": "l101",
      "numero": "101",
      "nome": "Linha exemplo",
      "cor": "#EAB308",
      "pontoIds": ["p1", "p2"],
      "operacao": "06:00 às 20:00",
      "intervalo": "A cada 20 min",
      "tracado": [
        [-3.65, -45.38],
        [-3.65, -45.37]
      ],
      "circular": false
    }
  ],
  "stops": [
    { "id": "p1", "nome": "Início", "referencia": "Rua A", "lat": -3.65, "lng": -45.38 },
    { "id": "p2", "nome": "Fim", "referencia": "Rua B", "lat": -3.65, "lng": -45.37 }
  ],
  "buses": [{ "id": "bus1", "prefixo": "101-01", "linhaId": "l101", "sentido": "Fim" }],
  "notices": []
}
```

Na pasta `backend`, execute:

```powershell
$env:FIRESTORE_EMULATOR_HOST = '127.0.0.1:8080'
functions/venv/Scripts/python.exe scripts/publish_passenger_catalog.py caminho/catalogo.json
```

A ferramenta recusa projetos/hosts externos, valida o arquivo inteiro antes da escrita e exige que os ônibus já existam no cadastro privado. Publica até 500 documentos em um lote atômico, substituindo somente os documentos listados. Não apaga itens omitidos. Para retirar um veículo da operação, encerre a telemetria; para retirar itens do catálogo, use administração explícita no emulador.

O validador recusa campos extras, IDs duplicados, coordenadas não finitas, referências ausentes, paradas fora da ordem, cor inválida, percurso sem comprimento e paradas a mais de 100 m do traçado. Frações são calculadas pelo backend. Traçados circulares precisam retornar a até 100 m do início. No Firestore os vértices são mapas `{lat,lng}`, pois arrays aninhados não são aceitos; o adaptador reconverte para `[lat,lng]`.

O traçado precisa ser obtido de vias reais e homologado pela operação. A validação geométrica não comprova sentidos de circulação, acessibilidade ou veracidade dos horários. A ferramenta não publica automaticamente os mocks como dados reais.

## GPS, ETA e estados

`sendTelemetry` mantém a autorização existente e busca a linha pública do ônibus. Projeta o GPS no segmento mais próximo do traçado, grava progresso, próximo ponto e previsões por parada no mesmo CAS da posição. Se não houver publicação, a telemetria operacional continua funcionando, mas o passageiro não recebe aquele veículo.

ETA = distância restante pelo traçado / velocidade instantânea. Não usa a localização do passageiro nem média fictícia de velocidade. Abaixo de 3,6 km/h, a mais de 100 m do traçado ou com `out_of_route`, não há ETA numérico. Percursos abertos não retornam artificialmente ao início. Circulares podem dar a volta. Cruzamentos e vias sobrepostas ainda podem exigir map matching com histórico; a projeção atual escolhe o segmento mais próximo.

Não existe fonte de ocupação no backend: a lotação é `desconhecida`. Ônibus sem nó está fora de serviço. Após 45 s sem heartbeat, a posição fica `connection_lost`, sem ETA. O frontend também expira o estado localmente e observa a conexão RTDB. O catálogo de veículos é observado para refletir vínculos novos sem reload; linhas e paradas são consultadas ao abrir/recarregar a tela.

No fim de viagem, use `endTelemetry` antes de `checkOut`. Exclusões de telemetria usam CAS com objeto vazio, que remove o nó RTDB. O SDK Python não aceita `None` em `set_if_unchanged`. Isso evita apagar um heartbeat concorrente do monitor. Firestore e RTDB são bancos distintos: a autorização no Firestore e a gravação no RTDB não formam uma transação distribuída; uma migração futura pode usar versão de sessão para reforçar a troca de motorista.

## Offline e publicação real

O service worker guarda o shell e tiles já visitados. Não guarda respostas REST de GPS/ETA. Firebase não habilita persistência Firestore em disco. Últimos dados em memória continuam visíveis com aviso; uma abertura offline nova pode não ter catálogo ou posições. Nenhuma tela deve interpretar erro de rede como zero ônibus ou posição atual.

Antes de usar produção, o responsável precisa habilitar o [provedor anônimo do Firebase](https://firebase.google.com/docs/auth/web/anonymous-auth), configurar domínio/chave/URL corretos, revisar catálogo real e publicar regras/functions em uma implantação coordenada. A ferramenta incluída é exclusivamente local. Não houve deploy nem alteração de produção nesta implementação.

Validação e comandos: [VALIDACAO.md](VALIDACAO.md). Contrato REST alternativo: [API.md](API.md).
