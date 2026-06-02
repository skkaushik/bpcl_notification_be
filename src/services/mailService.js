const transporter = require("../config/mailConfig");

const sendEmail = async ({ to, subject, text }) => {
  const mailOptions = {
    from: process.env.EMAIL_USER,
    to,
    subject,
    text,
  };

  const info = await transporter.sendMail(mailOptions);

  return info;
};

module.exports = { sendEmail };