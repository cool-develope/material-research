import { Outlet } from "react-router-dom";

import { ProfileMenu } from "./ProfileMenu";
import { ThemeToggle } from "./ThemeToggle";

export function Layout() {
  return (
    <>
      <div className="corner-actions">
        <ThemeToggle />
        <ProfileMenu />
      </div>
      <Outlet />
    </>
  );
}
