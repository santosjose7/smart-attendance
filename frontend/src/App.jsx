import { useState } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import LoginPage from './pages/auth/login';
import RegisterPage from './pages/auth/Register';
import './App.css'


function App() {
  

  return (
    <Routes>
        <Route path="/" element={< LoginPage />} />
        <Route path="/login" element={< LoginPage />} />
        <Route path="/register" element={< RegisterPage />} />
        
    </Routes>

    
   
  );

}

export default App
