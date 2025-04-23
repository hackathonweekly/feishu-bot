import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();

// Serve static files from public directory
app.use(express.static('public'));
// Serve check-in data
app.use('/data', express.static('data'));

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Check-in dashboard running at http://localhost:${PORT}/checkins.html`);
});