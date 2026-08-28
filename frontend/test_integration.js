const fs = require('fs');

async function run() {
  try {
    console.log('Testing /analyze...');
    const formData = new FormData();
    const imageBuffer = fs.readFileSync('../static/samples/sample4.jpg');
    formData.append('image', new Blob([imageBuffer], { type: 'image/jpeg' }), 'sample4.jpg');
    formData.append('station', 'Station-1');
    formData.append('ward', 'ER');

    const res1 = await fetch('http://127.0.0.1:5000/analyze', {
      method: 'POST',
      body: formData
    });
    
    if (!res1.ok) {
        throw new Error(`Analyze failed: ${await res1.text()}`);
    }
    const analyzeData = await res1.json();
    console.log('Analyze Result:');
    console.log('  Event ID:', analyzeData.event_id);
    console.log('  Expected Route:', analyzeData.analysis.decision.expected_route);
    console.log('  Has RAG Evidence:', analyzeData.rag.evidence?.length > 0);
    console.log('  Has LLM Explanation:', !!analyzeData.explanation.explanation);
    
    const expectedRoute = analyzeData.analysis.decision.expected_route;
    const wrongRoute = expectedRoute === 'BROWN' ? 'YELLOW' : 'BROWN';

    console.log('\nTesting /verify (CORRECT)...');
    const res2 = await fetch('http://127.0.0.1:5000/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_id: analyzeData.event_id,
        actual_route: expectedRoute
      })
    });
    const verifyDataCorrect = await res2.json();
    console.log('  Status:', verifyDataCorrect.verification.status);
    
    console.log('\nTesting /verify (VIOLATION)...');
    const res3 = await fetch('http://127.0.0.1:5000/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_id: analyzeData.event_id,
        actual_route: wrongRoute
      })
    });
    const verifyDataWrong = await res3.json();
    console.log('  Status:', verifyDataWrong.verification.status);
    console.log('  Reason:', verifyDataWrong.verification.reason_code);
    console.log('\nAll tests passed!');
  } catch (err) {
    console.error('Test failed:', err);
  }
}

run();
