import React, { useState } from 'react';
import axios from 'axios';

function Ranking() {
  const [data, setData] = useState([]);
  const [message, setMessage] = useState('');

  const handleFetchData = async () => {
    try {
      const response = await axios.get('https://your-api-endpoint.com/ranking');
      setData(response.data);
      setMessage('Dane pobrane pomyślnie!');
    } catch (error) {
      setMessage('Błąd podczas pobierania danych.');
    }
  };

  return (
    <div>
      <h1>Ranking</h1>
      <button onClick={handleFetchData}>Pobierz dane</button>
      <p>{message}</p>
      <table>
        <thead>
          <tr>
            <th>Imię</th>
            <th>Nazwisko</th>
            <th>Punkty</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item, index) => (
            <tr key={index}>
              <td>{item.imie}</td>
              <td>{item.nazwisko}</td>
              <td>{item.punkty}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default Ranking;
