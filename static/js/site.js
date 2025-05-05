// Manage the visibility
document.getElementById('visibilityButton').addEventListener('click', ()=> {
    const site = window.location.pathname.split('/').pop()
    fetch(`/sites_manager/visibility/${site}`)
    .then(response => response.json())
    .then(data => {
        console.log(data.state)
        if (data.state) {
            document.getElementById('visibilityButton').innerText = 'Hide the site'
        } else {
            document.getElementById('visibilityButton').innerText = 'Make the site visible'
        };
    });
});
