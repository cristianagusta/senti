import { useState, useEffect } from "react"
import { useLocation } from "react-router-dom"
import "../App.css"
import { API_URL } from "../config.js"

import logo from "../assets/logo.png"
import positiveIcon from "../assets/positive.png"
import negativeIcon from "../assets/negative.png"
import neutralIcon from "../assets/neutral.png"

function Analyze() {

  const [val, setVal] = useState("")
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [videoId, setVideoId] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const user = JSON.parse(localStorage.getItem("user"))
  const location = useLocation()

  const isValidYoutube = (url) => {
    return url.includes("youtube.com") || url.includes("youtu.be")
  }

  const getId = (url) => {
    try {
      if (url.includes("youtu.be")) return url.split("youtu.be/")[1].split("?")[0]
      const u = new URL(url)
      if (u.searchParams.get("v")) return u.searchParams.get("v")
      const parts = u.pathname.split("/")
      return parts[2]
    } catch {
      return null
    }
  }

  const getSentimentClass = (sentiment) => {
    if (!sentiment) return "Neutral"
    if (sentiment.includes("Positive")) return "Positive"
    if (sentiment.includes("Negative")) return "Negative"
    return "Neutral"
  }

  const getIcon = (sentiment) => {
    if (sentiment === "Positive") return positiveIcon
    if (sentiment === "Negative") return negativeIcon
    return neutralIcon
  }

  const percentage = (val) =>
    result ? parseFloat(((val / result.total) * 100).toFixed(1)) : 0

  const send = async () => {
    if (!isValidYoutube(val)) return

    const id = getId(val)
    if (!id) return

    setLoading(true)
    setResult(null)
    setSaved(false)

    const res = await fetch(`${API_URL}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: val })
    })

    const data = await res.json()

    const counts = data.summary.counts
    const total = data.summary.total

    setVideoId(data.video_id)

    setResult({
      sentiment: data.summary.overall,
      total,
      conclusion: data.summary.conclusion,
      Positive: counts.Positive || 0,
      Neutral: counts.Neutral || 0,
      Negative: counts.Negative || 0,
    })

    setLoading(false)
  }

  const save = async () => {
    setSaving(true)
    setSaved(false)

    await fetch(`${API_URL}/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user: user.email,
        videoId,
        result
      })
    })

    setSaving(false)
    setSaved(true)
  }

  useEffect(() => {
    if (location.state) {
      const item = location.state

      setVideoId(item.videoId)

      const counts = item.result.counts || {}
      const total = item.result.total || 0

      setResult({
        sentiment: item.result.overall,
        total,
        conclusion: item.result.conclusion,
        Positive: counts.Positive || 0,
        Neutral: counts.Neutral || 0,
        Negative: counts.Negative || 0,
      })
    }
  }, [location.state])

  return (
    <div className="page">

      <div className="app-container">

        <img src={logo} className="logo" />
        <p className="slogan">Turn URL into Sentiment.</p>

        <div className="input-outer">

          {!isValidYoutube(val) && val !== "" && (
            <p className="error-text">Invalid YouTube URL</p>
          )}

          <div className="input-row">
            <input
              value={val}
              onChange={(e) => setVal(e.target.value)}
              placeholder="Paste YouTube URL"
            />
            <button onClick={send} disabled={loading}>
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
              <p className="summary-section">{result.conclusion}</p>
            </div>

            {user && (
              <div className="action-buttons">
                <button className="save-btn" onClick={save} disabled={saving}>
                  {saving ? <div className="btn-spinner"></div> : "Save"}
                </button>

                <button
                  className="reset-btn"
                  disabled={saving}
                  onClick={() => window.location.reload()}
                >
                  Reset
                </button>
              </div>
            )}

            {saved && <p className="success">Saved Successfully</p>}

          </div>
        )}

      </div>
    </div>
  )
}

export default Analyze
