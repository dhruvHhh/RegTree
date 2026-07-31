import { NavLink } from "react-router-dom";
import { MessageCircle, FileText } from "lucide-react";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

function navClass({ isActive }: { isActive: boolean }) {
  return [
    "flex items-center gap-3 rounded-lg px-3 py-2.5 text-[15px] font-medium transition-colors",
    isActive ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5 hover:text-slate-200",
  ].join(" ");
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      {/* Backdrop — mobile only, when the drawer is open. */}
      {open && <div className="fixed inset-0 z-30 bg-black/60 md:hidden" onClick={onClose} />}

      <aside
        className={[
          "fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col border-r border-slate-800 bg-[#080b11] p-4 transition-transform",
          "md:static md:z-auto md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        ].join(" ")}
      >
        <div className="mb-8 px-2 py-2">
          <span className="text-2xl tracking-tight text-white">
            <span className="font-extrabold">Reg</span><span className="font-normal">Tree</span>
          </span>
        </div>

        <nav className="space-y-1">
          <NavLink to="/" end className={navClass} onClick={onClose}>
            <MessageCircle size={20} />
            New Chat
          </NavLink>
          <NavLink to="/documents" className={navClass} onClick={onClose}>
            <FileText size={20} />
            Documents
          </NavLink>
        </nav>
      </aside>
    </>
  );
}
