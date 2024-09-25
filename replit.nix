{ pkgs }: {
  deps = [
    pkgs.openssl
    pkgs.postgresql
    pkgs.rustc
    pkgs.libiconv
    pkgs.cargo
  ];
}