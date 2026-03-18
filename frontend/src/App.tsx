import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import BundleUpload from "./pages/BundleUpload";
import BundleDetail from "./pages/BundleDetail";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/upload" element={<BundleUpload />} />
          <Route path="/bundles/:id" element={<BundleDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
