// Manage the visibility
document.getElementById('visibilityButton').addEventListener('click', ()=> {
    const study = window.location.pathname.split('/').pop();
    fetch(`/studies_manager/visibility/${study}`)
    .then(response => response.json())
    .then(data => {
        console.log(data.state)
        if (data.state) {
            document.getElementById('visibilityButton').innerText = 'Hide the study'
        } else {
            document.getElementById('visibilityButton').innerText = 'Make the study visible'
        };
    });
});


// Modify the study
document.getElementById('modifyStudyButton').addEventListener('click', () => {
    const study = window.location.pathname.split('/').pop();
    window.location.href = `/studies_manager/modify/${study}`
});


// Delete the study
document.getElementById('deleteStudyButton').addEventListener('click', () => {
    delete_confirm = window.confirm('Are you sure you want to delete the study? Once deleted, you cannot go back.');
    if (delete_confirm) {
        const study = window.location.pathname.split('/').pop();
        fetch(`/studies_manager/delete/${study}`, {method: 'POST'})
        .then(response => response.json())
        .then(data => {
            window.location.href = '/studies_manager'
        });
    };
});