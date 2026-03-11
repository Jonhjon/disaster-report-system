import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/", label: "地圖總覽", icon: "🗺" },
  { to: "/report", label: "通報災情", icon: "📢" },
  { to: "/events", label: "災情列表", icon: "📋" },
  { to: "/help", label: "使用說明", icon: "❓" },
];

function Sidebar() {
  return (
    <aside className="w-48 border-r bg-white">
      <nav className="flex flex-col gap-1 p-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${
                isActive
                  ? "bg-red-50 font-semibold text-red-600"
                  : "text-gray-700 hover:bg-gray-100"
              }`
            }
          >
            <span>{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;
