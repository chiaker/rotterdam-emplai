import { useState } from 'react';
import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/auth';
import { Menu, X, Briefcase, FileText, Users, LogOut } from 'lucide-react';

export function Layout() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/vacancies', label: 'Вакансии', icon: Briefcase },
    { to: '/resumes', label: 'Резюме', icon: FileText },
    { to: '/matches', label: 'Мэтчи', icon: Users },
  ];

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo */}
            <div className="flex items-center">
              <Link to="/" className="text-xl font-bold text-primary-600">
                EmplAI
              </Link>
            </div>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex space-x-8">
              {navItems.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-700 hover:text-primary-600 transition-colors"
                >
                  <item.icon className="w-4 h-4 mr-1" />
                  {item.label}
                </Link>
              ))}
            </nav>

            {/* User Menu */}
            <div className="hidden md:flex items-center space-x-4">
              <span className="text-sm text-gray-600">{user?.email}</span>
              <button
                onClick={handleLogout}
                className="inline-flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-primary-600 transition-colors"
              >
                <LogOut className="w-4 h-4 mr-1" />
                Выйти
              </button>
            </div>

            {/* Mobile Menu Button */}
            <div className="md:hidden">
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="inline-flex items-center justify-center p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100"
              >
                {isMobileMenuOpen ? (
                  <X className="block h-6 w-6" />
                ) : (
                  <Menu className="block h-6 w-6" />
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Menu */}
        {isMobileMenuOpen && (
          <div className="md:hidden">
            <div className="pt-2 pb-3 space-y-1">
              {navItems.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={() => setIsMobileMenuOpen(false)}
                  className="block pl-3 pr-4 py-2 text-base font-medium text-gray-700 hover:text-primary-600 hover:bg-gray-50"
                >
                  <item.icon className="w-4 h-4 inline mr-2" />
                  {item.label}
                </Link>
              ))}
              <div className="pt-4 pb-4 border-t border-gray-200">
                <div className="px-4 text-sm text-gray-600">{user?.email}</div>
                <button
                  onClick={handleLogout}
                  className="mt-2 block w-full text-left px-4 py-2 text-base font-medium text-gray-700 hover:text-primary-600 hover:bg-gray-50"
                >
                  <LogOut className="w-4 h-4 inline mr-2" />
                  Выйти
                </button>
              </div>
            </div>
          </div>
        )}
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
}
