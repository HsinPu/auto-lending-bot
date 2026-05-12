type StatusCardProps = {
  label: string
  value: string | number
  tone?: 'safe' | 'danger'
}

export function StatusCard({ label, value, tone }: StatusCardProps) {
  return (
    <article className={`status-card ${tone ?? ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  )
}
