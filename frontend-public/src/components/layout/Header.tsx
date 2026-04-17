import { Link } from "react-router-dom";

function Header() {
  return (
    <header className="flex h-14 items-center justify-between border-b bg-red-600 px-6 text-white">
      <Link to="/" className="text-lg font-bold">
        智慧災害通報系統
      </Link>
      <Link
        to="/report"
        className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-red-600 hover:bg-red-50"
      >
        通報災情
      </Link>
    </header>
  );
}

export default Header;
