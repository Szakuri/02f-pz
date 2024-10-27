import logo from './logo.svg';
import './App.css';
import FileUpload from './FileUpload';
import Ranking from './Ranking';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <FileUpload />
        <Ranking />
      </header>
    </div>
  );
}

export default App;
