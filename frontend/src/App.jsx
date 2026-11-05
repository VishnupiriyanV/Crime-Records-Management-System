import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import Layout from './Layout.jsx';
import { useSession } from './session.jsx';
import { Loading } from './ui.jsx';
import { Login, Register } from './pages/Auth.jsx';
import { Notifications, Profile, Records } from './pages/Account.jsx';
import { Complaint, Complaints, NewComplaint } from './pages/Complaints.jsx';
import { Case, Cases, Dashboard } from './pages/Cases.jsx';
import { CriminalForm, Criminals } from './pages/Criminals.jsx';
import { Audit, Reports, Users } from './pages/Admin.jsx';
import { Search } from './pages/Search.jsx';
import NotFound from './pages/NotFound.jsx';

function Guard({ roles, children }) {
  const { user, ready } = useSession();
  const location = useLocation();
  if (!ready) return <Loading />;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  if (roles && !roles.includes(user.role)) return <NotFound forbidden />;
  return children;
}

function Home() {
  const { user, ready } = useSession();
  if (!ready) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === 'citizen' ? '/complaints' : '/dashboard'} replace />;
}

const staff = ['officer', 'admin'];

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/search" element={<Guard><Search /></Guard>} />
        <Route path="/profile" element={<Guard><Profile /></Guard>} />
        <Route path="/notifications" element={<Guard><Notifications /></Guard>} />
        <Route path="/records" element={<Guard><Records /></Guard>} />
        <Route path="/complaints" element={<Guard><Complaints /></Guard>} />
        <Route path="/complaints/new" element={<Guard roles={['citizen']}><NewComplaint /></Guard>} />
        <Route path="/complaints/:id" element={<Guard><Complaint /></Guard>} />
        <Route path="/dashboard" element={<Guard roles={staff}><Dashboard /></Guard>} />
        <Route path="/cases" element={<Guard roles={staff}><Cases /></Guard>} />
        <Route path="/cases/:id" element={<Guard roles={staff}><Case /></Guard>} />
        <Route path="/criminals" element={<Guard roles={staff}><Criminals /></Guard>} />
        <Route path="/criminals/new" element={<Guard roles={staff}><CriminalForm /></Guard>} />
        <Route path="/criminals/:id" element={<Guard roles={staff}><CriminalForm /></Guard>} />
        <Route path="/reports" element={<Guard roles={['admin']}><Reports /></Guard>} />
        <Route path="/users" element={<Guard roles={['admin']}><Users /></Guard>} />
        <Route path="/audit" element={<Guard roles={['admin']}><Audit /></Guard>} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
