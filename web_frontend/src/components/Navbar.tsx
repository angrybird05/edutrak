import { Bell, Search, User, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

const roleColors: Record<string, string> = {
  admin: "from-primary to-accent",
  teacher: "from-emerald-500 to-teal-500",
  student: "from-amber-500 to-orange-500",
  parent: "from-rose-500 to-pink-500",
};

const Navbar = () => {
  const navigate = useNavigate();
  const { role, userName, logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <header className="h-16 glass-strong border-b border-white/[0.08] flex items-center justify-between px-6 sticky top-0 z-30">
      {/* Search */}
      <div className="flex-1 max-w-md">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search..."
            className="w-full glass-input pl-10 pr-4 py-2 text-sm"
          />
        </div>
      </div>

      {/* Right */}
      <div className="flex items-center gap-3">
        <Button variant="glass" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-[10px] text-white flex items-center justify-center font-bold">
            3
          </span>
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="glass" className="gap-2 px-3">
              <div className={`w-7 h-7 rounded-lg bg-gradient-to-br ${roleColors[role || "admin"]} flex items-center justify-center`}>
                <User className="h-4 w-4 text-white" />
              </div>
              <div className="hidden md:block text-left">
                <span className="text-sm font-medium block leading-tight">{userName}</span>
                <span className="text-[10px] text-muted-foreground capitalize">{role}</span>
              </div>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end"
            className="w-48 glass-strong border border-white/[0.12] bg-background/90 backdrop-blur-xl">
            <DropdownMenuItem className="hover:bg-white/[0.06] cursor-pointer">
              <User className="mr-2 h-4 w-4" /> Profile
            </DropdownMenuItem>
            <DropdownMenuSeparator className="bg-white/[0.08]" />
            <DropdownMenuItem className="hover:bg-white/[0.06] cursor-pointer text-red-400" onClick={handleLogout}>
              <LogOut className="mr-2 h-4 w-4" /> Logout
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
};

export default Navbar;
