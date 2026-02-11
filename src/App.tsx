import { Suspense } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { AppRoutes } from './router';

function App() {
  return (
    <BrowserRouter basename={__BASE_PATH__}>
      <Suspense fallback={
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-950 via-red-950 to-purple-900">
          <div className="text-center">
            <img 
              src="https://static.readdy.ai/image/d55f7533e2770f6cf984b3b0dd8016a8/0f4cef46158b860125e33f2644b930f5.png" 
              alt="JOKA" 
              className="w-24 h-24 object-contain mx-auto mb-6 animate-pulse drop-shadow-2xl"
            />
            <div className="w-16 h-16 border-4 border-orange-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-purple-300 text-sm font-medium">A carregar sistema JOKA...</p>
          </div>
        </div>
      }>
        <AppRoutes />
      </Suspense>
    </BrowserRouter>
  );
}

export default App;