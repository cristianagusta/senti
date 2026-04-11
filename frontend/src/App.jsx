import { useState } from 'react'
import './App.css'

function App() {
  const [val, setVal] = useState("")
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [videoId, setVideoId] = useState(null)

  const changeVal = (event) => {
    setVal(event.target.value)
  }

  const isValidYoutube = (url) => {
    return url.includes("youtube.com/watch?")
  }

  const getYoutubeVideoId = (url) => {
    try {
      const parsed = new URL(url)
      return parsed.searchParams.get("v")
    } catch {
      return null
    }
  }

  const isValid = isValidYoutube(val)

  const refreshPage = () => {
    window.location.reload()
  }

  const sendRequest = async () => {
    if (!isValid) return

    try {
      setLoading(true)
      setResult(null)

      const id = getYoutubeVideoId(val)
      setVideoId(id)

      await fetch("http://127.0.0.1:8000/scrapping", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: val }),
      })

      const response = await fetch("http://127.0.0.1:8000/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: val }),
      })

      const data = await response.json()

      const sentiment = data.summary.overall
      const counts = data.summary.counts
      const total = data.summary.total
      const conclusion = data.summary.conclusion

      setResult({
        sentiment,
        total,
        conclusion,
        positive: counts.positive || 0,
        neutral: counts.neutral || 0,
        negative: counts.negative || 0,
      })

    } catch (error) {
      console.error("Error:", error)
      setResult({ message: "Something went wrong" })
    } finally {
      setLoading(false)
      setVal("")
    }
  }

  return (
    <div className="chat-container">

      <div className="header" onClick={refreshPage}>
        <h1 className="logo">Senti</h1>
      </div>

      <div className="chat-body">

        {!loading && !result && (
          <div className="slogan-container">
            <p className="slogan">
              Turn your URL into Sentiment
            </p>
          </div>
        )}

        {loading && (
          <div className="result-box loading-box">
            <div className="spinner"></div>
            <p className="loading-text">
              Analyzing<span className="dots"></span>
            </p>
          </div>
        )}

        {result && result.message && !loading && (
          <div className="result-box">
            <p>{result.message}</p>
          </div>
        )}

        {result && result.sentiment && !loading && (
          <div className="result-box">

            {videoId && (
              <div className="player-wrapper">
                <iframe
                  className="player"
                  src={`https://www.youtube.com/embed/${videoId}`}
                  title="YouTube player"
                  frameBorder="0"
                  allowFullScreen
                ></iframe>
              </div>
            )}

            <p className="main-result">
              The majority of sentiment is{" "}
              <strong>
                {result.sentiment.charAt(0).toUpperCase() + result.sentiment.slice(1)}
              </strong>
            </p>

            <div className="stats">
              <p>Total Comments: {result.total}</p>
              <p>Positive: {result.positive}</p>
              <p>Neutral: {result.neutral}</p>
              <p>Negative: {result.negative}</p>
            </div>

            <p className="conclusion">
              The conclusion is{" "}
              {result.conclusion.charAt(0).toLowerCase() + result.conclusion.slice(1)}
            </p>
          </div>
        )}
      </div>

      <div className="chat-input">
        <div className="input-wrapper">

          {!isValid && val !== "" && (
            <p className="error-text">
              Submitted URL is not Youtube's
            </p>
          )}

          <div className="input-row">
            <input
              type="text"
              placeholder="Paste URL..."
              value={val}
              onChange={changeVal}
            />

            <button onClick={sendRequest} disabled={loading || !isValid}>
              →
            </button>
          </div>

          <p className="note-text">
            Submitted URL should be YouTube's
          </p>

        </div>
      </div>

    </div>
  )
}

export default App