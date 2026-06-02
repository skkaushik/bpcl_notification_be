const express = require("express");
const cors = require("cors");
require("dotenv").config();

const mailRoutes = require("./routes/mailRoutes");

const app = express();

app.use(cors());
app.use(express.json());

app.use("/api", mailRoutes);

app.get("/test", (req, res) => {
  res.json({
    success: true,
    message: "Backend Working"
  });
});

const PORT = process.env.PORT || 5000;

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});