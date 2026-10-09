import "@fontsource/outfit/500.css";
import "@fontsource/outfit/700.css";
import "@fontsource/outfit/900.css";
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/700.css";
import "@fontsource/jetbrains-mono/400.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import Home from "@/pages/Home";
import RegisterDisplay from "@/pages/RegisterDisplay";
import RegisterAdmin from "@/pages/RegisterAdmin";
import BibleDisplay from "@/pages/BibleDisplay";
import BibleAdmin from "@/pages/BibleAdmin";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/register" element={<RegisterDisplay />} />
        <Route path="/register-admin" element={<RegisterAdmin />} />
        <Route path="/bible" element={<BibleDisplay />} />
        <Route path="/bible-admin" element={<BibleAdmin />} />
        <Route path="*" element={<Home />} />
      </Routes>
      <Toaster theme="dark" position="bottom-right" richColors closeButton />
    </BrowserRouter>
  );
}

export default App;
