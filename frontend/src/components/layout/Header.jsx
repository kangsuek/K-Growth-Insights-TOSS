import { useState } from "react";
import { Link, useLocation } from "react-router-dom";

const NAV_LINKS = [
  { to: "/", label: "대시보드" },
  { to: "/scanner", label: "스크리닝" },
  { to: "/compare", label: "비교" },
  { to: "/simulation", label: "시뮬레이션" },
  { to: "/portfolio", label: "포트폴리오" },
  { to: "/alerts", label: "알림" },
  { to: "/settings", label: "설정" },
];

const NAV_ACTIVE = "bg-primary-500 text-white shadow-md";
const NAV_INACTIVE =
  "text-gray-600 hover:bg-primary-50 hover:text-primary-600 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-primary-400";

export default function Header() {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const linkClass = (to) =>
    `px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
      location.pathname === to ? NAV_ACTIVE : NAV_INACTIVE
    }`;

  return (
    <header className="bg-white dark:bg-gray-800 shadow-sm sticky top-0 z-50 transition-colors">
      <nav className="container mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="h-10 w-10 rounded-lg bg-primary-500 text-white flex items-center justify-center font-bold">
              K
            </div>
            <div>
              <h1 className="text-lg font-bold leading-tight">K-Growth Insights TOSS</h1>
              <p className="text-xs text-gray-500 dark:text-gray-400 leading-tight">
                토스증권 Open API 기반 종목 분석
              </p>
            </div>
          </Link>

          <div className="hidden md:flex items-center gap-1">
            {NAV_LINKS.map((link) => (
              <Link key={link.to} to={link.to} className={linkClass(link.to)}>
                {link.label}
              </Link>
            ))}
          </div>

          <button
            className="md:hidden p-2 rounded-lg text-gray-600 dark:text-gray-300"
            aria-label="메뉴 열기"
            onClick={() => setMobileMenuOpen((v) => !v)}
          >
            {mobileMenuOpen ? "✕" : "☰"}
          </button>
        </div>

        {mobileMenuOpen && (
          <div className="md:hidden mt-3 pb-3 flex flex-col gap-1 animate-slideDown">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={linkClass(link.to)}
                onClick={() => setMobileMenuOpen(false)}
              >
                {link.label}
              </Link>
            ))}
          </div>
        )}
      </nav>
    </header>
  );
}
