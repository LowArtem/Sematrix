const bulletItems = [
  "Postgres with pgvector",
  "Redis for Celery broker and results",
  "Ollama for local models",
  "FastAPI backend",
  "Celery worker and beat",
  "React frontend build served by Nginx",
]

export default function App() {
  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">Sematrix MVP</p>
        <h1>Local-first notes runtime scaffold</h1>
        <p className="lede">
          The Docker Compose baseline is up, so future stories can fill in the
          backend API, workers, and note UI on top of a running stack.
        </p>
      </section>

      <section className="card">
        <h2>Services in this compose stack</h2>
        <ul>
          {bulletItems.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </main>
  )
}
