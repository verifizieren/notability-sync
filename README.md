# Notability Dashboard

This project is a web application for managing and sharing Notability links. It provides a user-friendly interface to add, view, sync, and delete Notability entries, as well as generate public shareable links.

## Features

- Add new Notability links
- View and sync entries
- Auto-sync entries at specified intervals
- Delete entries with confirmation
- Generate and copy public shareable links

## Technologies Used

- HTML/CSS for the frontend
- Flask for the backend
- Docker for containerization

## Getting Started

### Prerequisites

- Docker and Docker Compose installed on your machine

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-username/notability-dashboard.git
   cd notability-dashboard
   ```

2. **Build and run the application using Docker Compose:**

   ```bash
   docker-compose up --build
   ```

3. **Access the application:**

   Open your web browser and go to `http://localhost:5177`.

### Configuration

- Ensure that the `app.py` and other configuration files are set up correctly for your environment.
- Modify the `docker-compose.yml` if you need to change any service configurations.

## Usage

- **Add Entry:** Click on "Add new Notability link" to add a new entry.
- **View PDF:** Click on "View PDF" to open the PDF in a new tab.
- **Sync Entry:** Click on "Sync" to manually sync an entry.
- **Delete Entry:** Click on "Delete" to remove an entry after confirmation.
- **Copy Link:** Use the "Copy Link" button to copy the public shareable link to your clipboard.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For any questions or feedback, please contact [your-email@example.com](mailto:your-email@example.com). 
