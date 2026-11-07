# Script for populating the database. You can run it as:
#
#     mix run priv/repo/seeds.exs
#
# Inside the script, you can read and write to any of your
# repositories directly:
#
#     Tcc.Repo.insert!(%Tcc.SomeSchema{})
#
# We recommend using the bang functions (`insert!`, `update!`
# and so on) as they will fail if something goes wrong.
alias Tcc.Repo
alias Tcc.Sensors.Unit

units_data = [
  %{
    name: "Temperature",
    symbol: "°C",
    description: "Degrees Celsius - standard measure of ambient or object heat"
  },
  %{
    name: "Humidity",
    symbol: "%",
    description: "Relative humidity percentage - measure of moisture content in air"
  },
  %{
    name: "Pressure",
    symbol: "hPa",
    description: "Hectopascals - barometric atmospheric pressure"
  },
  %{
    name: "Co2",
    symbol: "ppm",
    description: "Parts per million - carbon dioxide concentration level"
  },
  %{
    name: "Voc",
    symbol: "ppb",
    description: "Parts per billion - volatile organic compounds concentration"
  },
  %{
    name: "Pms",
    symbol: "µg/m³",
    description: "Micrograms per cubic meter - airborne particulate matter density"
  },
  %{
    name: "Illuminance",
    symbol: "lx",
    description: "Lux - light intensity hitting a surface"
  },
  %{
    name: "Uv",
    symbol: "index",
    description: "UV index - solar ultraviolet radiation strength"
  },
  %{
    name: "Noise",
    symbol: "dB",
    description: "Decibels - ambient sound level"
  },
  %{
    name: "Analog",
    symbol: "ADC",
    description: "Analog-to-Digital Converter raw numerical count"
  },
  %{
    name: "Voltage",
    symbol: "V",
    description: "Volts - electrical potential difference"
  }
]

IO.puts("Seeding units...")

Enum.each(units_data, fn attrs ->
  case Repo.get_by(Unit, name: attrs.name) do
    nil ->
      %Unit{}
      |> Unit.changeset(attrs)
      |> Repo.insert!()

    existing ->
      existing
      |> Unit.changeset(attrs)
      |> Repo.update!()
  end
end)

IO.puts("Units seeded successfully!")
