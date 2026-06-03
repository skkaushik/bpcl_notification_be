const nodemailer = require("nodemailer");

const transporter = nodemailer.createTransport({
  host: "smtp.gmail.com",
  port: 587,          // changed from 465
  secure: false,      // false for 587 (STARTTLS)
  auth: {
    user: process.env.EMAIL_USER,
    pass: process.env.EMAIL_PASS,
  },
  connectionTimeout: 30000,
  socketTimeout: 30000,
  tls: {
    rejectUnauthorized: false
  },
  family: 4,          // force IPv4
});

module.exports = transporter;