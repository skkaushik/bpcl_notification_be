const { sendEmail } = require("../services/mailService");

const sendMail = async (req, res) => {
  console.log("========== API HIT ==========");
  console.log(req.body);

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
  console.error("========== MAIL ERROR ==========");
  console.error(error);
  console.error(error.message);

  res.status(500).json({
    success: false,
    message: error.message,
  });
}              
};

module.exports = { sendMail };