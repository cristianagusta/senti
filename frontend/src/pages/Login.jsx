import { useState } from "react"
import { API_URL } from "../config"
import { useNavigate } from "react-router-dom"
import "../App.css"
import logo from "../assets/logo.png"

function Login() {

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

  const nav = useNavigate()

  const isValidEmail = (email) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
  }

  const submit = async () => {

    setError("")

    const r = await fetch(`${API_URL}/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        email,
        password
      })
    })

    const d = await r.json()

    if (!r.ok) {
      setError(d.detail)
      return
    }

    localStorage.setItem(
      "user",
      JSON.stringify(d)
    )

    nav("/")
  }

  return (
    <div className="auth-page">

      <img src={logo} className="auth-logo-outside" />

      <div className="auth-card">

        <label>Email</label>

        <input
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
        />

        {email !== "" && !isValidEmail(email) && (
          <p className="error-text">
            Invalid Email
          </p>
        )}

        <label>Password</label>

        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
        />

        <button
          onClick={submit}
          disabled={!isValidEmail(email)}
        >
          Login
        </button>

        {error && (
          <p className="error-text">
            {error}
          </p>
        )}

        <p className="auth-switch">
          Don’t Have an Account?{" "}
          <span onClick={() => nav("/signup")}>
            Sign Up
          </span>
        </p>

      </div>

    </div>
  )
}

export default Login
