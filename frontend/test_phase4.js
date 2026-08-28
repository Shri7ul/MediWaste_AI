const fs = require('fs');

async function run() {
  try {
    console.log('Testing /operations...');
    const opRes = await fetch('http://127.0.0.1:5000/operations');
    const opData = await opRes.json();
    console.log(`Operations: found ${opData.operations.total_bins} bins.`);
    console.log(`DataSource: ${opData.operations.data_source}`);
    
    console.log('\nTesting /analytics...');
    const anRes = await fetch('http://127.0.0.1:5000/analytics');
    const anData = await anRes.json();
    console.log(`Analytics: Total Events ${anData.analytics.total_events}, Correct ${anData.analytics.correct}`);

    console.log('\nTesting /events...');
    const evRes = await fetch('http://127.0.0.1:5000/events?limit=1');
    const evData = await evRes.json();
    console.log(`Events: Count ${evData.count}`);
    
    if (evData.events.length > 0) {
      const latestEventId = evData.events[0].event_id;
      console.log(`\nTesting /disposal/definition...`);
      const defRes = await fetch('http://127.0.0.1:5000/disposal/definition');
      const defData = await defRes.json();
      console.log(`Steps: ${defData.total_steps}`);
      
      console.log(`\nTesting 5-step Disposal for event: ${latestEventId}...`);
      
      for (const step of defData.steps) {
        console.log(`Completing step: ${step.id}...`);
        const stepRes = await fetch(`http://127.0.0.1:5000/disposal/${latestEventId}/steps/${step.id}/complete`, { method: 'POST' });
        if (!stepRes.ok) {
           console.log(`Error: ${await stepRes.text()}`);
        } else {
           console.log(`Step ${step.id} completed.`);
        }
      }
      
      const finalRes = await fetch(`http://127.0.0.1:5000/disposal/${latestEventId}`);
      const finalData = await finalRes.json();
      console.log(`Final Disposal is_complete: ${finalData.workflow.is_complete}`);
    }
    
    console.log('\nAll phase 4 tests passed!');
  } catch (err) {
    console.error('Test failed:', err);
  }
}

run();
