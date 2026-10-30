const paths = {
  document: ['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z', 'M14 2v6h6M8 12h8M8 16h5'],
  upload: ['M12 16V4m-4 4 4-4 4 4', 'M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4'],
  arrow: ['M5 12h14m-5-5 5 5-5 5'],
  check: ['m5 12 4 4L19 6'],
  search: ['M21 21l-4.5-4.5', 'M19 10.5a8.5 8.5 0 1 1-17 0 8.5 8.5 0 0 1 17 0'],
  book: ['M12 5v16M3 3h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5v16h-5a4 4 0 0 0-4 2 4 4 0 0 0-4-2H3Z'],
  chat: ['M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-3 3V11.5a10 10 0 0 1 20 0Z', 'M7 10h8M7 14h5'],
  grid: ['M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z'],
  external: ['M15 3h6v6m0-6L10 14', 'M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5'],
  shield: ['M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7Z', 'm8 12 3 3 5-6'],
  info: ['M12 11v6M12 7h.01', 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0'],
  globe: ['M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M3 12h18', 'M12 3c5 5 5 13 0 18-5-5-5-13 0-18'],
  quote: ['M10 5H3v7h5c0 3-2 5-5 6M21 5h-7v7h5c0 3-2 5-5 6'],
}

export default function Icon({ name, size = 20, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      {(paths[name] || paths.document).map((d, index) => <path key={index} d={d} />)}
    </svg>
  )
}
