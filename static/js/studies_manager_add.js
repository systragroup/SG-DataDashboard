// Submit the form and create the study
document.getElementById('submitStudyButton').addEventListener('click', () => {

    // Check the form completion
    let correctFill = true;
    document.getElementById('formStudy').querySelectorAll('[required]').forEach(input => {
        if (!input.value) {
            correctFill = false;
            return;
        };
    });
    if (!correctFill) {
        alert('Not all the required fields are filled.')
    } else {

        // Create the study
        const form = document.getElementById('formStudy');
        const formData = new FormData(form);
        fetch('/studies_manager/create', {
            method: 'POST',
            body: formData,
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                window.location.href = `/study/${data.study}`
            }
        });
        
    };
});