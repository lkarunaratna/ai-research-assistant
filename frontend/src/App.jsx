import React, { useState, useEffect } from 'react'; // Added useEffect
import './App.css';

function App() {
  const [researchTopic, setResearchTopic] = useState('');
  const [output, setOutput] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Store the EventSource instance
  const [eventSource, setEventSource] = useState(null);

  // Cleanup function for EventSource
  useEffect(() => {
    return () => {
      if (eventSource) {
        console.log("Cleanup: Closing EventSource.");
        eventSource.close();
      }
    };
  }, [eventSource]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!researchTopic.trim()) return;

    // Close any existing EventSource before starting a new one
    if (eventSource) {
      eventSource.close();
      setEventSource(null); // Clear the old EventSource
    }

    setOutput([]);
    setIsLoading(true);
    setError(null);
    console.log("Starting research. isLoading = true");

    try {
      // EventSource expects a GET request to initiate the stream
      const newEventSource = new EventSource(`http://localhost:8001/api/v1/research?query=${encodeURIComponent(researchTopic)}`);
      setEventSource(newEventSource);

      newEventSource.onopen = () => {
        console.log("EventSource connection opened.");
      };

      newEventSource.onmessage = (event) => {
        // This will catch any events that don't have a specific event type listener
        console.log("Received unhandled message event:", event.data);
      };

      // Add listeners for specific event types
      const eventTypes = [
        'llm_full_response', 'tool_start', 'tool_end', 'agent_action', 
        'agent_finish', 'agent_reasoning_start', 'final_research_output'
      ];

      eventTypes.forEach(type => {
        newEventSource.addEventListener(type, (event) => {
          try {
            const eventData = JSON.parse(event.data);
            console.log(`Received event: ${type}`, eventData);
            setOutput((prev) => [...prev, { type: type, data: eventData }]);
          } catch (e) {
            console.error(`Error parsing ${type} data:`, e, event.data);
          }
        });
      });

      newEventSource.addEventListener('workflow_end', (event) => {
        console.log("Received event: workflow_end. Closing EventSource.");
        if (newEventSource) {
          newEventSource.close();
          console.log("EventSource closed.");
        }
        setIsLoading(false); // Reset isLoading here
        console.log("Finished research. isLoading = false");
      });

      newEventSource.onerror = (err) => {
        console.error("EventSource error:", err);
        // EventSource doesn't provide detailed error objects directly.
        // The readyState can give some hints:
        // 0: CONNECTING, 1: OPEN, 2: CLOSED
        const errorState = newEventSource.readyState;
        let errorMessage = `Stream error (readyState: ${errorState}).`;
        if (errorState === EventSource.CLOSED) {
          errorMessage += " Connection was closed.";
        } else if (errorState === EventSource.CONNECTING) {
          errorMessage += " Attempting to reconnect or failed to connect.";
        }
        setError(errorMessage + " Check browser console and network tab for details.");
        
        if (newEventSource) {
          newEventSource.close();
        }
        setIsLoading(false);
        console.log("Caught EventSource error. isLoading = false");
      };
      
    } catch (e) {
      console.error('Failed to initialize EventSource:', e);
      setError(e.message);
      setIsLoading(false);
      console.log("Caught error during EventSource initialization. isLoading = false");
    } finally {
      // With EventSource, the state is managed by its event listeners (workflow_end, onerror)
      console.log("handleSubmit outer finally block reached.");
      // The isLoading state should be managed by the 'workflow_end' event listener.
      // This block will execute immediately after new EventSource() or if it fails to initialize.
      // It does NOT wait for the EventSource to finish streaming.
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>AI Research Assistant</h1>
        <p>
          This AI Research Assistant helps you gather, organize, and summarize information from multiple sources on a given topic.
        </p>
      </header>

      <main className="App-main">
        <form onSubmit={handleSubmit} className="research-form">
          <input
            type="text"
            value={researchTopic}
            onChange={(e) => setResearchTopic(e.target.value)}
            placeholder="Enter your research topic (e.g., 'climate change impact on agriculture')"
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading}>
            {isLoading ? 'Researching...' : 'Start Research'}
          </button>
        </form>

        {error && <div className="error-message">Error: {error}</div>}

        <div className="output-section">
          <h2>Research Output</h2>
          {output.length === 0 && !isLoading && !error && (
            <p>Enter a topic above to start a new research.</p>
          )}
          {isLoading && <p>Loading...</p>}
          
          {output.map((item, index) => (
            <div key={index} className={`output-item output-item-${item.type}`}>
              <strong>{item.type.replace(/_/g, ' ')}:</strong>{' '}
              {item.type === 'llm_full_response' ? (
                <div dangerouslySetInnerHTML={{ __html: item.data.content }} />
              ) : item.type === 'tool_start' ? (
                <span>Tool Start: {item.data.tool_name} with input: {item.data.input}</span>
              ) : item.type === 'tool_end' ? (
                <span>Tool End: {item.data.output}</span>
              ) : item.type === 'agent_action' ? (
                <span>Agent Action: {item.data.tool} with input: {item.data.tool_input}</span>
              ) : item.type === 'agent_finish' ? (
                <span>Agent Finished. Output: {JSON.stringify(item.data.output)}</span>
              ) : item.type === 'agent_reasoning_start' ? (
                <span>Agent is reasoning...</span>
              ) : item.type === 'final_research_output' ? (
                <pre>{JSON.stringify(item.data, null, 2)}</pre>
              ) : item.type === 'error' ? (
                <span>Error: {item.data.message || JSON.stringify(item.data)}</span>
              ) : (
                <span>{JSON.stringify(item.data)}</span>
              )
              }
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

export default App;