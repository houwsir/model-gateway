import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import Overview from './pages/Overview';
import Routing from './pages/Routing';
import Providers from './pages/Providers';
import Balancing from './pages/Balancing';
import Traffic from './pages/Traffic';
import Memory from './pages/Memory';
import Resilience from './pages/Resilience';
import Alerts from './pages/Alerts';
import Settings from './pages/Settings';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<Overview />} />
        <Route path="/routing" element={<Routing />} />
        <Route path="/providers" element={<Providers />} />
        <Route path="/balancing" element={<Balancing />} />
        <Route path="/traffic" element={<Traffic />} />
        <Route path="/memory" element={<Memory />} />
        <Route path="/resilience" element={<Resilience />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/overview" replace />} />
      </Route>
    </Routes>
  );
}
