const { sendEmail } = require("../services/mailService");

const sendMail = async (req, res) => {
  try {
    const { to, subject, text } = req.body;

    await sendEmail({
      to,
      subject,
      text,
    });

    res.status(200).json({
      success: true,
      message: "Email sent successfully",
    });
  } catch (error) {
    console.error(error);

    res.status(500).json({
      success: false,
      message: error.message,
    });
  }
};

module.exports = { sendMail };