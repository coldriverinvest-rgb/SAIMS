import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import AdminApp from "./AdminApp";
import "./styles.css";
import "./enhancements.css";
import "./finance-controls.css";
import "./financial-analysis.css";
import "./stock-analysis.css";
import "./admin.css";
import "./layout-fixes.css";

const RootApp = window.location.pathname.startsWith("/admin") ? AdminApp : App;

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode><RootApp /></React.StrictMode>,
);
