
import { useEffect, useState } from "react"
import { API_URL } from "../config.js"
import { useNavigate } from "react-router-dom"
import "../App.css"

function History() {

  const [data, setData] = useState([])

  const user = JSON.parse(
    localStorage.getItem("user")
  )

  const nav = useNavigate()

  useEffect(() => {

    if (!user) return

    fetch(`${API_URL}/history/${user.email}`, {
      headers: {
        Authorization: `Bearer ${user.token}`
      }
    })
      .then(res => res.json())
      .then(setData)

  }, [])

  return (
    <div className="page">

      <div className="history-container">

        <div className="history-card">

          {data.length === 0 && (
            <p className="history-no">
              No Data Available
            </p>
          )}

          {data.map((item, index) => (

            <div
              key={index}
              className="history-item"
              onClick={() =>
                nav("/result", {
                  state: {
                    videoId: item.videoId,
                    result: item.result
                  }
                })
              }
            >

              <p className="history-title">
                {item.title || item.videoId}
              </p>

              <p className="history-time">
                {new Date(item.createdAt).toLocaleString()}
              </p>

            </div>

          ))}

        </div>

      </div>

    </div>
  )
}

export default History
