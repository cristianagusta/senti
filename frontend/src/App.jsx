import { useState } from 'react'
import './App.css'
import { API_URL } from './config'

import logo from './assets/logo.png'
import bg from './assets/background.png'
import positiveIcon from './assets/positive.png'
import negativeIcon from './assets/negative.png'
import neutralIcon from './assets/neutral.png'

function App() {
  const [val, setVal] = useState("")
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [videoId, setVideoId] = useState(null)

  const isValidYoutube = (url) => url.includes("youtube.com/watch?")

  const getYoutubeVideoId = (url) => {
    try {
      const parsed = new URL(url)
      return parsed.searchParams.get("v")
    } catch {
      return null
    }
  }

  const getSentimentClass = (sentiment) => {
    if (!sentiment) return "Neutral";

    const s = sentiment;

    if (s.includes("Positive")) return "Positive";
    if (s.includes("Negative")) return "Negative";
    return "Neutral";
  };

  const refreshPage = () => {
    window.location.reload()
  }

  const getIcon = (sentiment) => {
    if (sentiment === "Positive") return positiveIcon
    if (sentiment === "Negative") return negativeIcon
    return neutralIcon
  }

  const sendRequest = async () => {
    if (!isValidYoutube(val)) return

    try {
      setLoading(true)
      setResult(null)

      const id = getYoutubeVideoId(val)
      setVideoId(id)

      const response = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: val }),
      })

      const data = await response.json()

      const counts = data.summary.counts
      const total = data.summary.total

      setResult({
        sentiment: data.summary.overall,
        total,
        conclusion: data.summary.conclusion,
        Positive: counts.Positive || 0,
        Neutral: counts.Neutral || 0,
        Negative: counts.Negative || 0,
      })

    } catch {
      setResult({ message: "Something went wrong" })
    } finally {
      setLoading(false)
    }
  }

  const percentage = (val) => result ? parseFloat(((val / result.total) * 100).toFixed(1)) : 0

  return (
    <div className="app-container">

      <img src={logo} className="logo" onClick={refreshPage} />
      <p className="slogan">Turn URL into Sentiment.</p>

      <div className="input-outer">

        {!isValidYoutube(val) && val !== "" && (
          <p className="error-text">Invalid YouTube URL</p>
        )}

        <div className="input-row">
          <input
            value={val}
            onChange={(e) => setVal(e.target.value)}
            placeholder="Paste Your Youtube URL Here"
          />

          <button onClick={sendRequest} disabled={loading}>
            {loading ? <div className="btn-spinner"></div> : "→"}
          </button>
        </div>

      </div>

      {result && (
        <div className="result-box">

          {videoId && (
            <iframe
              className="player"
              src={`https://www.youtube.com/embed/${videoId}`}
              allowFullScreen
            />
          )}

          <hr />

          <div className="overall-section">
            <img src={getIcon(result.sentiment)} className="emoji" />
            <div>
              <p className="label">Overall Sentiment</p>
              <p className={`value ${getSentimentClass(result.sentiment)}`}>
                {result.sentiment}
              </p>
            </div>
          </div>

          <hr />

          <div className="breakdown">
            <p className="section-title">Sentiment Breakdown</p>

            {["Positive", "Negative", "Neutral"].map((type) => (
              <div key={type} className="bar-group">
                <div className="bar-header">
                  <span>{type}</span>
                  <span>{percentage(result[type])}%</span>
                </div>
                <div className="bar-bg">
                  <div
                    className={`bar-fill ${type}`}
                    style={{ width: `${percentage(result[type])}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>

          <div className="summary">
            <p className="section-title">Summary</p>
            <p>{result.conclusion}</p>
          </div>

        </div>
      )}

    </div>
  )
}




export default App
