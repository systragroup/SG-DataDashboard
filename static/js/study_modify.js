// Process the modifications
document.getElementById('submitModifButton').addEventListener('click', () => {
    modif_confirm = window.confirm('Are you sure you want to modify the study? Once done, you cannot go back.');
    if (modif_confirm) {

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

            // Submit the modifications
            const form = document.getElementById('formStudy');
            const formData = new FormData(form);
            const study = window.location.pathname.split('/').pop();
            fetch(`/study/submit_modif/${study}`, {
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
    };
});