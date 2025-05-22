// See the study when clicked on
document.addEventListener('DOMContentLoaded', () => {

    fetch('/datajs/studies')
    .then(response => response.json())
    .then(data => {

        // If there are studies, create one event listener per location
        if (data.length > 0) {
            data.forEach(id => {
                document.getElementById(`div${id}`).addEventListener('click', () => {
                    window.location.href = `/study/${id}`
                });
            });
        };

    });
});


// Add location button
document.getElementById('addStudyButton').addEventListener('click', () => {
    window.location.href = '/studies_manager/add'
});