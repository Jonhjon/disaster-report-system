import { Routes, Route } from "react-router-dom";
import Header from "./components/layout/Header";
import Sidebar from "./components/layout/Sidebar";
import MapPage from "./pages/MapPage";
import ReportPage from "./pages/ReportPage";
import HelpPage from "./pages/HelpPage";

function App() {
  return (
    <div className="flex h-screen flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto bg-gray-50 p-4">
          <Routes>
            <Route path="/" element={<MapPage />} />
            <Route path="/report" element={<ReportPage />} />
            <Route path="/help" element={<HelpPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default App;
