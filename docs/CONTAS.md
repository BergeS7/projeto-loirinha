# Contas, acesso e operação

## Telas

A navegação principal tem o item **Conta**. As rotas são `/conta/login`, `/conta/cadastro`, `/conta/recuperar`, `/conta/perfil`, `/conta/motorista` e `/conta/frota`. O login direciona pelo papel da custom claim. Rotas operacionais não renderizam controles de outro perfil e todas as operações privilegiadas são autorizadas novamente no servidor. O passageiro continua podendo consultar o mapa sem uma conta permanente.

Os formulários oferecem estados de envio, erro, confirmação de senha e resposta neutra de recuperação. Não armazenam senhas em localStorage nem as registram em logs. Com Firebase ausente, as telas continuam visíveis com aviso de indisponibilidade e envio desabilitado. Não existe autenticação fictícia no modo mock.

## Configuração necessária

Use as variáveis Firebase de `.env.example` mesmo que a fonte de transporte continue `mock`. Para uso local, configure `VITE_USE_EMULATORS=true` e inicie Auth, Firestore, RTDB e Functions. As treze callables usam `southamerica-east1`. Em produção, habilite e-mail/senha e o provedor anônimo no Firebase Authentication, configure domínio autorizado e publique as functions/regras em uma implantação coordenada. Nenhum deploy foi executado por esta implementação.

No Auth Emulator, links de recuperação aparecem no console do emulador; não são e-mails reais. Em produção, configure os modelos de e-mail e valide entrega e recuperação no domínio autorizado antes de liberar usuários.

## Cadastro de passageiro

O SDK cria a identidade de e-mail ou vincula credenciais à sessão anônima existente. A callable `registerPassenger({name})` cria o perfil `users/{uid}` e atribui exclusivamente `passageiro`, preservando outras claims. Nenhum campo `role` ou frota é aceito do navegador. Contas operacionais existentes são recusadas. Depois da conclusão, o cliente atualiza o token.

Auth e Firestore são serviços separados. Se a conclusão falhar após a identidade ser criada, a conta permanece autenticada como cadastro pendente: entre novamente e use **Concluir cadastro de passageiro**. Essa ação é repetível; não tente criar outra identidade com o mesmo e-mail. Favoritos existentes continuam locais e não são sincronizados entre aparelhos.

## Dono de frota e motoristas

O primeiro dono deve ser provisionado por administração confiável: identidade Auth, claim `role=dono_frota` e `users/{uid}.fleet_owner_id=uid`. Não há autoinscrição de dono nem botão para transformar um passageiro em dono.

| Callable nova       | Autorização e finalidade                                                                     |
| ------------------- | -------------------------------------------------------------------------------------------- |
| `registerPassenger` | Identidade com e-mail, sem papel operacional: concluir o próprio perfil                      |
| `listFleetUsers`    | Dono: primeiros 100 motoristas da própria frota e indicador de lista incompleta              |
| `listFleetRoutes`   | Dono: até 100 opções de rotas privadas da própria frota                                      |
| `createDriver`      | Dono: cria identidade, claim motorista e documentos users/drivers vinculados à própria frota |
| `setDriverActive`   | Dono: altera somente o estado ativo de um motorista da própria frota                         |

O dono cadastra nome/e-mail, envia a definição de senha por recuperação, ativa/desativa motoristas e escolhe uma rota pelo nome. O sistema não entrega senha provisória ao dono: gera segredo aleatório no servidor e o titular define sua senha pelo e-mail. E-mails existentes não são apropriados nem transferidos entre frotas. Para associar uma identidade já existente, será necessário um fluxo separado de convite com consentimento.

A criação utiliza lote Firestore para os documentos e compensa falhas de persistência removendo a identidade Auth recém-criada. Por não haver transação distribuída, falhas de rede com confirmação ambígua exigem conferir Auth e os documentos antes de repetir manualmente. As regras continuam impedindo escrita direta do navegador em users, drivers e buses. O diretório global de usuários não fica acessível aos donos.

## Operação do motorista

O painel recupera o ônibus com check-in ativo e a rota atribuída. O motorista informa a tag para assumir um veículo; nenhuma frota ou identidade vem do formulário. **Iniciar envio de GPS** solicita permissão do navegador e envia posição a cada 15 segundos enquanto a tela está aberta. Valores de velocidade do navegador são convertidos de m/s para km/h. Fixes com mais de 45 segundos não viram heartbeat novo.

Pausar GPS, sair da tela ou sair da conta interrompe a captura e limpa o intervalo. Isso não libera o veículo automaticamente. Para encerrar o serviço, use **Encerrar expediente**, que chama `endTelemetry` antes de `checkOut`. Motorista desativado pode continuar usando o check-out; se `endTelemetry` for recusada por inatividade, a liberação ainda é permitida e o monitor remove a posição antiga. A PWA não garante execução em segundo plano ou com o celular bloqueado: homologar aplicativo nativo/serviço de localização é uma etapa distinta.

## Testes

`pnpm test` cobre login, confirmação de senha e recuperação, além das regressões anteriores. `python -m unittest discover -s backend/tests_unit -v` cobre autorização, isolamento de frota, preservação de claims e compensação de criação, usando doubles sem rede. Os fluxos reais de envio de e-mail, criação Auth e GPS em aparelho precisam ser homologados com os emuladores completos e depois no ambiente de destino.
