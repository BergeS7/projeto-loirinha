/** Tela de busca (/buscar): procura linhas e pontos por texto e guarda as buscas recentes. */
import { Clock3, MapPin, Search, X } from "lucide-react"
import { type FormEvent, useState } from "react"
import { Link } from "react-router"
import { paths } from "../app/paths"
import EmptyState from "../components/ui/EmptyState"
import ErrorState from "../components/ui/ErrorState"
import PageHeader from "../components/ui/PageHeader"
import RouteBadge from "../components/ui/RouteBadge"
import { BUSCA_DEBOUNCE_MS } from "../config/constants"
import { useBusca } from "../hooks/transit"
import useDebouncedValue from "../hooks/useDebouncedValue"
import { getBuscasRecentes, salvarBuscaRecente } from "../services/preferences"

/** Busca enquanto o usuário digita (com debounce). Sem texto, mostra as buscas recentes. */
export default function SearchPage() {
  const [term, setTerm] = useState("")
  const [recents, setRecents] = useState(getBuscasRecentes)
  const debouncedTerm = useDebouncedValue(term, BUSCA_DEBOUNCE_MS)
  const search = useBusca(debouncedTerm)

  const hasTerm = term.trim().length > 0
  // Enquanto o usuário digita, o termo ainda não chegou à busca (debounce): mostra "Buscando..." e esconde resultados antigos.
  const typing = term.trim() !== debouncedTerm.trim()
  const loading = hasTerm && (typing || search.loading)
  const results = hasTerm && !typing ? search.data : undefined
  const total = results ? results.linhas.length + results.pontos.length : 0

  const rememberSearch = () => setRecents(salvarBuscaRecente(term))

  const submit = (event: FormEvent) => {
    event.preventDefault()
    rememberSearch()
  }

  return (
    <div className="page page-soft">
      <PageHeader title="Buscar" subtitle="Linha, ponto ou destino" />
      <div className="page-body search-page-body">
        <form className="search-field" onSubmit={submit} role="search">
          <Search size={21} />
          <input
            autoFocus
            type="search"
            enterKeyHint="search"
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Ex.: 101, Rodoviária..."
            aria-label="Buscar linha, ponto ou destino"
          />
          {term && (
            <button type="button" onClick={() => setTerm("")} aria-label="Limpar busca">
              <X size={19} />
            </button>
          )}
        </form>

        {!hasTerm && (
          <>
            <div className="section-heading roomy">
              <h2>Buscas recentes</h2>
            </div>
            {recents.length > 0 ? (
              <div className="card-list">
                {recents.map((recent) => (
                  <button type="button" key={recent} className="simple-row" onClick={() => setTerm(recent)}>
                    <Clock3 size={19} />
                    <span>{recent}</span>
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState
                variant="compact"
                icon={<Search size={28} />}
                title="Encontre sua melhor rota"
                description="Pesquise pelo número da linha, nome do ponto ou destino."
              />
            )}
          </>
        )}

        {loading && (
          <div className="search-loading" role="status">
            <span className="loader" /> Buscando...
          </div>
        )}

        {!loading && hasTerm && search.error !== undefined && <ErrorState error={search.error} onRetry={search.reload} />}

        {results && total === 0 && (
          <EmptyState icon={<Search size={30} />} title="Nada encontrado" description="Tente outro nome ou confira se o número está correto." />
        )}

        {results && results.linhas.length > 0 && (
          <section>
            <div className="section-heading roomy">
              <h2>Linhas</h2>
              <span>{results.linhas.length}</span>
            </div>
            <div className="card-list">
              {results.linhas.map((line) => (
                <Link to={paths.linha(line.id)} key={line.id} className="result-row" onClick={rememberSearch}>
                  <RouteBadge linha={line} />
                  <span>
                    <strong>{line.nome}</strong>
                    <small>{line.intervalo}</small>
                  </span>
                </Link>
              ))}
            </div>
          </section>
        )}

        {results && results.pontos.length > 0 && (
          <section>
            <div className="section-heading roomy">
              <h2>Pontos e destinos</h2>
              <span>{results.pontos.length}</span>
            </div>
            <div className="card-list">
              {results.pontos.map((point) => (
                <Link to={paths.ponto(point.id)} key={point.id} className="result-row" onClick={rememberSearch}>
                  <span className="round-icon">
                    <MapPin size={19} />
                  </span>
                  <span>
                    <strong>{point.nome}</strong>
                    <small>{point.referencia}</small>
                  </span>
                </Link>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
