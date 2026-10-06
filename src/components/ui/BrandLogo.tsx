/** Símbolo da marca. Para trocar a logo, substitua public/icons/logo.svg (e gere os PNGs, veja o README). */
export default function BrandLogo({ size = 38, className = "" }: { size?: number; className?: string }) {
  return (
    <img
      className={`brand-logo ${className}`}
      src={`${import.meta.env.BASE_URL}icons/logo.svg`}
      width={size}
      height={size}
      alt=""
      aria-hidden="true"
      draggable={false}
    />
  )
}
