export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{fontFamily:'ui-sans-serif, system-ui', margin:0, padding:20}}>
        <h1>RFP Proposal Platform</h1>
        <nav style={{marginBottom:20}}>
          <a href="/">Home</a> | <a href="/upload">Upload</a>
        </nav>
        {children}
      </body>
    </html>
  )
}
