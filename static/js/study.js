// Manage the visibility
document.getElementById('visibilityButton').addEventListener('click', ()=> {
    const study = window.location.pathname.split('/').pop();
    fetch(`/study/visibility/${study}`)
    .then(response => response.json())
    .then(data => {
        if (data.state) {
            document.getElementById('visibilityButton').innerText = 'Hide the study';
        } else {
            document.getElementById('visibilityButton').innerText = 'Make the study visible';
        };
    });
});


// Add a file
document.getElementById('addFileButton').addEventListener('click', () => {
    const study = window.location.pathname.split('/').pop();
    window.location.href = `/study/add_file/${study}`;
});


// Modify the study
document.getElementById('modifyStudyButton').addEventListener('click', () => {
    const study = window.location.pathname.split('/').pop();
    window.location.href = `/study/modify/${study}`;
});


// Delete the study
document.getElementById('deleteStudyButton').addEventListener('click', () => {
    delete_confirm = window.confirm('Are you sure you want to delete the study? Once deleted, you cannot go back.');
    if (delete_confirm) {
        const study = window.location.pathname.split('/').pop();
        fetch(`/study/delete/${study}`, {method: 'POST'})
        .then(response => response.json())
        .then(data => {
            window.location.href = '/studies_manager';
        });
    };
});