// Display the correct form for each type of file
document.getElementById('typeFileSelector').addEventListener('change', () => {
    // Hide all the divs
    const divs = document.querySelectorAll('[id^="divType"]');
    for (i = 0; i < divs.length; i++) {
        divs[i].style.display = "none";
    };

    // Display only the good one
    const selected = document.getElementById('typeFileSelector').value;
    document.getElementById(`divType${selected}`).style.display = "block";
});