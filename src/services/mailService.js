const transporter = require("../config/mailConfig");

const sendEmail = async ({ to, subject, text }, retries = 3) => {
  const mailOptions = {
    from: process.env.EMAIL_USER,
    to,
    subject,
    text,
  };

  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const info = await transporter.sendMail(mailOptions);
      console.log("========== EMAIL SENT SUCCESSFULLY ==========");
      console.log("Message ID:", info.messageId);
      return info;
    } catch (error) {
      console.error(`Attempt ${attempt}/${retries} failed:`, error.message);
      
      if (attempt === retries) {
        throw error;
      }
      
      // Wait before retrying (exponential backoff)
      const delay = Math.pow(2, attempt) * 1000;
      console.log(`Retrying in ${delay}ms...`);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
};

module.exports = { sendEmail };