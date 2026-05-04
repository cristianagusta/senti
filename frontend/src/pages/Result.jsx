import { useLocation } from "react-router-dom"
import "../App.css"

import positiveIcon from "../assets/positive.png"
import negativeIcon from "../assets/negative.png"
import neutralIcon from "../assets/neutral.png"

function Result() {
  const { state } = useLocation()

  if (!state) return <p>No Data</p>

  const { videoId, result } = state

  const counts = result.counts || {
    Positive: result.Positive || 0,
    Negative: result.Negative || 0,
    Neutral: result.Neutral || 0
  }

  const sentiment = result.overall || result.sentiment

  const getIcon = (s) => {
    if (s === "Positive") return positiveIcon
    if (s === "Negative") return negativeIcon
    return neutralIcon
  }

  const percentage = (v) => {
    if (!result.total) return 0
    return ((v / result.total) * 100).toFixed(1)
  }

  return (
    <div className="page">
      <div className="app-container">

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
            <img src={getIcon(sentiment)} className="emoji" />
            <div>
              <p className="label">Overall Sentiment</p>
              <p className={`value ${sentiment}`}>
                {sentiment}
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
                  <span>{percentage(counts[type])}%</span>
                </div>

                <div className="bar-bg">
                  <div
                    className={`bar-fill ${type}`}
                    style={{ width: `${percentage(counts[type])}%` }}
                  ></div>
                </div>

              </div>
            ))}
          </div>

          <div className="summary">
            <p className="section-title">Summary</p>
            <p className="summary-section">{result.conclusion}</p>
          </div>

        </div>

      </div>
    </div>
  )
}

export default Result
