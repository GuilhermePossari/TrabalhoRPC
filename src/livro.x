#define PROGRAM_NUMBER 1111111
#define VERSION_NUMBER 1

struct livro
{
        int numero;
        string nome<100>;
        string categoria<50>;
        int copias;
};

program ADDSUB_PROG
{
   version ADDSUB_VERSION
   {
     int ADD (operands) = 1;
     int SUB (operands) = 2;
   }
   = VERSION_NUMBER;
}
= PROGRAM_NUMBER;

