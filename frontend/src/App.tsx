import { useState } from "react";
import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
import { Menu } from "lucide-react";
import Sidebar from "./components/Sidebar";
import HomeView from "./components/HomeView";
import DocumentsPage from "./components/DocumentsPage";
import Workspace from "./components/Workspace";

function Shell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-[#050505] text-slate-200">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar — hidden on desktop where the sidebar is always visible. */}
        <header className="flex items-center gap-3 border-b border-slate-800 px-4 py-3 md:hidden">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
            className="text-slate-300 hover:text-white"
          >
            <Menu size={22} />
          </button>
          <span className="text-xl tracking-tight text-white">
            <span className="font-extrabold">Reg</span><span className="font-normal">Tree</span>
          </span>
        </header>

        <main className="min-h-0 flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<HomeView />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/workspace/:docId" element={<Workspace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
