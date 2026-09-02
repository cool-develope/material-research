import { NavLink, Outlet } from "react-router-dom";

export function Layout() {
  return (
    <div className="shell">
      <header className="top">
        <NavLink to="/" className="brand">
          Material Platform
        </NavLink>
        <nav>
          <NavLink to="/" end>
            Search
          </NavLink>
          <NavLink to="/chat">Deep Research</NavLink>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
