import { Link } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";

function Header() {
  const { user, logout } = useAuth();

  return (
    <header className="flex h-14 items-center justify-between border-b bg-blue-700 px-6 text-white">
      <Link to="/" className="text-lg font-bold">
        智慧災害通報系統 — 管理中心
      </Link>
      <div className="flex items-center gap-4">
        <span className="text-sm">{user?.display_name || user?.username}</span>
        <button
          onClick={logout}
          className="rounded-lg bg-white/20 px-3 py-1.5 text-sm hover:bg-white/30"
        >
          登出
        </button>
      </div>
    </header>
  );
}

export default Header;
