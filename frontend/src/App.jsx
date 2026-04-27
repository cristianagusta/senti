import { Routes, Route, useNavigate, useLocation } from "react-router-dom"
import Analyze from "./pages/Analyze"
import Login from "./pages/Login"
import Signup from "./pages/Signup"
import History from "./pages/History"
import Result from "./pages/Result"
import "./App.css"

import historyIcon from "./assets/history.png"
import backIcon from "./assets/back.png"

function App() {
  const nav = useNavigate()
  const location = useLocation()

  const user = JSON.parse(localStorage.getItem("user"))

  const showNavbar = ["/", "/history", "/result"].includes(location.pathname)

  return (
    <div>

      {showNavbar && (
        <div className="navbar">

          {/* LEFT ICON */}
          <img
            src={
              location.pathname === "/history" || location.pathname === "/result"
                ? backIcon
                : historyIcon
            }
            className="nav-icon"
            onClick={() => {
              if (location.pathname === "/history") {
                nav("/")
              } else if (location.pathname === "/result") {
                nav("/history")
              } else {
                nav("/history")
              }
            }}
          />

          {/* CENTER USER */}
          <div className="nav-center">
            {user ? user.username : ""}
          </div>

          {/* RIGHT BUTTON */}
          <div className="nav-right">
            {user ? (
              <div
                className="auth-btn"
                onClick={() => {
                  localStorage.removeItem("user")
                  window.location.reload()
                }}
              >
                Logout
              </div>
            ) : (
              <div className="auth-btn" onClick={() => nav("/login")}>
                Login
              </div>
            )}
          </div>

        </div>
      )}

      <Routes>
        <Route path="/" element={<Analyze />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/history" element={<History />} />
        <Route path="/result" element={<Result />} />
      </Routes>

    </div>
  )
}

export default App
