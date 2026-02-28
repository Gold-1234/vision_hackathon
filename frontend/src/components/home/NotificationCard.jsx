function NotificationCard({ value }) {
  return (
    <div className="flex items-center justify-between py-3 px-4 bg-grey-trans rounded-xl">
      <p className="p1">{value.text}</p>
      <p className="small neutral">{value.timestamp}</p>
    </div>
  );
}

export default NotificationCard;
