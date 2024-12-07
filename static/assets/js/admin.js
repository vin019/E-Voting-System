let currentCandidateId;
let currentPosition;

function openModal(position, candidateId) {
    currentPosition = position;
    currentCandidateId = candidateId;

    const candidateDiv = document.getElementById(`${position}_candidate${candidateId}`) || document.getElementById(`${position} ${candidateId}`);

    document.getElementById('editName').value = candidateDiv.querySelector('h4').innerText;
    document.getElementById('editPosition').value = candidateDiv.querySelector('p').innerText;
    document.getElementById('myModal').style.display = 'block';
}

function closeModal() {
    document.getElementById('myModal').style.display = 'none';
}

document.getElementById('saveBtn').addEventListener('click', function(event) {
    event.preventDefault();
    saveCandidate();
});

function saveCandidate() {
    const candidateName = document.getElementById('editName').value;
    const candidatePosition = document.getElementById('editPosition').value;

    const candidateDiv = document.getElementById(`${currentPosition}_candidate${currentCandidateId}`) || document.getElementById(`${currentPosition} ${currentCandidateId}`);

    candidateDiv.querySelector('h4').innerText = candidateName;
    candidateDiv.querySelector('p').innerText = candidatePosition;

    closeModal();
}
let votes = {
    president1: { name: '', count: 0 },
    president2: { name: '', count: 0 },
    president3: { name: '', count: 0 },
    vicePresident1: { name: '', count: 0 },
    vicePresident2: { name: '', count: 0 },
    vicePresident3: { name: '', count: 0 },
    secretary1: { name: '', count: 0 },
    secretary2: { name: '', count: 0 },
    secretary3: { name: '', count: 0 },
    treasurer1: { name: '', count: 0 },
    treasurer2: { name: '', count: 0 },
    treasurer3: { name: '', count: 0 },
    auditor1: { name: '', count: 0 },
    auditor2: { name: '', count: 0 },
    auditor3: { name: '', count: 0 },
    pio1: { name: '', count: 0 },
    pio2: { name: '', count: 0 },
    pio3: { name: '', count: 0 },
    representative1st1: { name: '', count: 0 },
    representative1st2: { name: '', count: 0 },
    representative1st3: { name: '', count: 0 },
    representative2nd1: { name: '', count: 0 },
    representative2nd2: { name: '', count: 0 },
    representative2nd3: { name: '', count: 0 },
    representative3rd1: { name: '', count: 0 },
    representative3rd2: { name: '', count: 0 },
    representative3rd3: { name: '', count: 0 },
    representative4th1: { name: '', count: 0 },
    representative4th2: { name: '', count: 0 },
    representative4th3: { name: '', count: 0 },
};

function vote(position, candidateNumber) {

    if (position.startsWith('president')) {
        votes[`president${candidateNumber}`].count++;
    } else if (position.startsWith('vice')) {
        votes[`vicePresident${candidateNumber}`].count++;
    } else if (position.startsWith('secretary')) {
        votes[`secretary${candidateNumber}`].count++;
    } else if (position.startsWith('treasurer')) {
        votes[`treasurer${candidateNumber}`].count++;
    } else if (position.startsWith('auditor')) {
        votes[`auditor${candidateNumber}`].count++;
    } else if (position.startsWith('pio')) {
        votes[`pio${candidateNumber}`].count++;
    } else if (position.startsWith('representative')) {
        const repNumber = parseInt(position.split('representative')[1]);
        votes[`representative${repNumber}th${candidateNumber}`].count++;
    }
}

function viewResults() {
    const resultsContent = document.getElementById('resultsContent');
    const resultsContainer = document.getElementById('results')

    if (resultsContainer.style.display === 'block') {
        resultsContainer.style.display = 'none';
    } else {
        resultsContent.innerHTML = '';

    const positions = [
        { name: 'President', prefix: 'president' },
        { name: 'Vice-President', prefix: 'vicePresident' },
        { name: 'Secretary', prefix: 'secretary' },
        { name: 'Treasurer', prefix: 'treasurer' },
        { name: 'Auditor', prefix: 'auditor' },
        { name: 'P.I.O', prefix: 'pio' },
        { name: '1st Representative', prefix: 'representative1st' },
        { name: '2nd Representative', prefix: 'representative2nd' },
        { name: '3rd Representative', prefix: 'representative3rd' },
        { name: '4th Representative', prefix: 'representative4th' },
    ];

    positions.forEach(position => {
        const positionVotes = Object.entries(votes)
            .filter(([key]) => key.startsWith(position.prefix))
            .map(([key, count]) => `<p>${key.replace(position.prefix, '').replace(/\d/, '')}: ${count} votes</p>`)
            .join('');

        resultsContent.innerHTML += `
            <div>
                <div class="position-title">${position.name}</div>
                ${positionVotes}
            </div>
            `;
        });

        resultsContainer.style.display = 'block';
    }
}