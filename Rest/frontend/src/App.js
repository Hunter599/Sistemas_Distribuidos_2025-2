import logo from './logo.svg';
import './App.css';

import React, { useState, useEffect } from 'react';

const API_URL = 'http://localhost:5000'
const CLIENT_ID = "client1";

// --- HELPER FUNCTION ---
const toLocalISOString = (date) => {
  const pad = (num) => (num < 10 ? '0' + num : num);
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hours = pad(date.getHours());
  const minutes = pad(date.getMinutes());
  return `${year}-${month}-${day}T${hours}:${minutes}`;
};


function App() {

  const defaultStartTime = new Date(Date.now() + 5000);
  const defaultEndTime = new Date(Date.now() + 60000);

  // State variables
  const [description, setDescription] = useState('');
  const [startTime, setStartTime] = useState(Date.now() / 1000 + 5);
  const [endTime, setEndTime] = useState(Date.now() / 1000 + 60);

  const [bidValues, setBidValues] = useState({});
  const [auctions, setAuctions] = useState([]);
  const [notifications, setNotifications] = useState([]);

  const [clientId, setClientId] = useState("client1");
  const [isConnected, setIsConnected] = useState(false);

  
  useEffect(() => {

    // Only connect if it is 'logged in' 
    if (!isConnected || !clientId) 
    {
      return; // if not connected do nothing
    }

    // connecting to event stream using the dynamic client ID
    const eventSource = new EventSource(`${API_URL}/stream/${clientId}`);

    // Real time notifications
    eventSource.onmessage = (event) => 
    {
      const eventData = JSON.parse(event.data);
      
      // Add the new notification to the top of the notification list
      setNotifications((prev) => [eventData, ...prev]);

      // Refresh auction list on new valid bid
      if (eventData.type === 'lance_validado') {
        fetchAuctions();
      }
    };

    // Cleans up the connection when the log out
    return () => {
      console.log(`SSE connection closed for ${clientId}`);
      eventSource.close();

    };

  }, [clientId, isConnected]) // This means that this effect is evoked when any of these two variable changes

  // Async fetching fuction, it gets the auctions from ms_leilao
  const fetchAuctions = async () => {
    try{
      const response = await fetch(`${API_URL}/leiloes`);
      const data = await response.json();
      setAuctions(data);
    } catch (error) {
      console.error("Error fetching auctions: ", error);
    }
  };

  // Fetches auctions when the app first connects
  useEffect(() => {
    if (isConnected){
      fetchAuctions();
    }
  }, [isConnected]);

  const handleCreateAuction = async(event) => {
    event.preventDefault();

    console.log("Create button clicked")

    // Convert local date strings back to Unix timestamps
    const startTimestamp = Math.floor(new Date(startTime).getTime() / 1000);
    const endTimestamp = Math.floor(new Date(endTime).getTime() / 1000);
    
    const auctionData = 
    {
      id: `auction-${Date.now()}`,
      description,
      start_time: startTimestamp,
      end_time: endTimestamp,
    };

    console.log("Sending auction data:", auctionData);

    // Sends information via post 
    try {
      await fetch(`${API_URL}/leiloes`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json' },
        body: JSON.stringify(auctionData)
      });

      console.log("Fetch successful! Refreshing auctions.");

      // Refreshes the auction list after creating a new one
      fetchAuctions();
    
    } catch(error) {
      console.error("Error creating auction: ", error);
    }

  };
  
  // Function that handles the bidding
  const handlePlaceBid = async(event, auctionId) => {
    event.preventDefault();

    const bidData = {
      auction_id: auctionId,
      user_id: clientId,
      bid_value: parseInt(bidValues[auctionId] || 0),
    };

    // Sends the data via post to the ms_lance 
    try {
      await fetch(`${API_URL}/lances`, 
      {
        method: 'POST',
        headers: {'Content-Type': 'application/json' },
        body: JSON.stringify(bidData),

      });
    
    } catch (error) 
    {
      console.error("Error placing bid: ", error);
    }
  };

  // Function that saves that the user is typing on the bid value box
  const handleBidChange = (auctionId, value) => 
  {
    setBidValues((prev) => 
    ({
      ...prev,
      [auctionId]: value,
    }));
  };

  // If not connected show a simple login box
  if (!isConnected) {
    return (
      <div style={{ padding: '50px', textAlign: 'center' }}>
        <h2>Enter Your Client ID</h2>
        <input
          type="text"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          placeholder="e.g., client1"
        />
        <button onClick={() => setIsConnected(true)}>Connect</button>
      </div>
    );
  }

  // Functions that handles the registration of interest of auctions
  const handleRegisterInterest = async (auctionId) => {
    
    // Sends the interested client's ID
    try {
      await fetch(`${API_URL}/auctions/${auctionId}/subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_id: clientId }), // Send our client ID
      });
      
      console.log(`Successfully registered for auction: ${auctionId}`);
    } catch (error) {
      console.error("Error registering interest:", error);
    }
  };

  return (
    <div style={{ display: 'flex', fontFamily: 'Arial, sans-serif' }}>
      <div style={{ flex: 1, padding: '20px' }}>
        <h2>Welcome, {clientId}</h2>
        <button onClick={() => setIsConnected(false)}>Disconnect</button>

        {/*  Auction form */}
        <div style={{ border: '1px solid #ccc', padding: '10px', marginBottom: '20px', marginTop: '10px' }}>
          <h3>Create New Auction</h3>
          <form onSubmit={handleCreateAuction}>
            <div>
              <label>Description: </label>
              <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
            <div>
              <label>Start Time: </label>
              <input type="datetime-local" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
            </div>
            <div>
              <label>End Time: </label>
              {/*  */}
              <input type="datetime-local" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
            </div>
            <button type="submit">Create</button>
          </form>
        </div>

        {/*  */}
        <h3>Active Auctions</h3>
        <button onClick={fetchAuctions}>Refresh List</button>
        <div style={{ marginTop: '10px' }}>
          {auctions.map((auction) => (
            <div key={auction.id} style={{ border: '1.5px solid #ddd', padding: '10px', marginBottom: '10px' }}>
              <strong>{auction.description} (ID: {auction.id})</strong>
              <p>Ends at: {new Date(auction.end_time * 1000).toLocaleTimeString()}</p>
              <button 
                onClick={() => handleRegisterInterest(auction.id)} 
                style={{marginRight: '10px'}}
              >
                Follow
              </button>
              <form onSubmit={(e) => handlePlaceBid(e, auction.id)}>
                <input
                  type="number"
                  placeholder="Your bid"
                  value={bidValues[auction.id] || ''}
                  onChange={(e) => handleBidChange(auction.id, e.target.value)}
                />
                <button type="submit">Place Bid</button>
              </form>
            </div>
          ))}
        </div>
      </div>

      {/*  */}
      <div style={{ flex: 1, padding: '20px', borderLeft: '2px solid #000' }}>
        <h3>Real-Time Notifications</h3>
        {notifications.map((notif, index) => (
          <div key={index} style={{ background: '#f4f4f4', border: '1px solid #ddd', padding: '8px', marginBottom: '8px' }}>
            <strong>{notif.type}</strong>
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {JSON.stringify(notif.data, null, 2)}
            </pre>
            {notif.type === 'link_pagamento' && (
              <a href={notif.data.payment_link} target="_blank" rel="noopener noreferrer">
                Click here to pay
              </a>
            )}
          </div>
        ))}
      </div>
    </div>

    
  );
}

export default App;