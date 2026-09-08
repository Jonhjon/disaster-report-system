import { NavLink } from "react-router-dom";
import { Map, ClipboardList, BarChart2, PieChart, HelpCircle, type LucideIcon } from "lucide-react";

const navItems: { to: string; label: string; Icon: LucideIcon }[] = [
  { to: "/", label: "地圖總覽", Icon: Map },
  { to: "/events", label: "災情列表", Icon: ClipboardList },
  { to: "/statistics", label: "統計分析", Icon: PieChart },
  { to: "/llm-logs", label: "LLM 日誌", Icon: BarChart2 },
  { to: "/help", label: "使用說明", Icon: HelpCircle },
];

function Sidebar() {
  return (
    <aside className="w-48 border-r bg-white">
      <nav aria-label="主要導航" className="flex flex-col gap-1 p-2">
        {navItems.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${
                isActive
                  ? "bg-blue-50 font-semibold text-blue-700"
                  : "text-gray-700 hover:bg-gray-100"
              }`
            }
          >
            <Icon size={16} aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;
