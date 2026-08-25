import { Navigate, Route, Routes } from "react-router-dom";
import AdminLayout from "./pages/AdminLayout";
import AdminOrders from "./pages/AdminOrders";
import AdminOrderDetail from "./pages/AdminOrderDetail";
import AdminCatalog from "./pages/AdminCatalog";
import AdminServiceEditor from "./pages/AdminServiceEditor";
import CustomerOrder from "./pages/CustomerOrder";
import Confirmation from "./pages/Confirmation";
import ServiceCatalog from "./pages/ServiceCatalog";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<ServiceCatalog />} />
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<Navigate to="orders" replace />} />
        <Route path="orders" element={<AdminOrders />} />
        <Route path="orders/:id" element={<AdminOrderDetail />} />
        <Route path="catalog" element={<AdminCatalog />} />
        <Route path="catalog/new" element={<AdminServiceEditor />} />
        <Route path="catalog/:slug" element={<AdminServiceEditor />} />
        <Route path="*" element={<Navigate to="orders" replace />} />
      </Route>
      <Route path="/order/:id" element={<CustomerOrder />} />
      <Route path="/order/:id/confirmation" element={<Confirmation />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
